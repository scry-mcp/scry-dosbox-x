"""What every section of `dosbox_x_live_matrix.py` shares: the server imported from the
files on disk, the one ledger of the run, what a reply has to look like, and the ways a
session is brought up, stopped where the matrix needs it, and ended.

Importing it puts the package's directory on the path, so the matrix calls the tool functions
in process, each one with the envelope the MCP layer returns. The SDK's schema check sits in
front of that and is not exercised here.
"""
from __future__ import annotations

import atexit
import contextlib
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

PKG = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PKG))

from matrix_ledger import Cell, Ledger  # noqa: E402
from scry_core import reply_contract as contract  # noqa: E402

import dosbox_session as ds  # noqa: E402
import dosbox_state as dstate  # noqa: E402
import dosbox_x_server as server  # noqa: E402

__all__ = ["ds", "server"]

M = Ledger()
ENV = dict(os.environ)

GUEST = PKG / "tests" / "guest"
PROBE_CONF = GUEST / "probe.conf"

#: Every session's bound: a backstop, `close` ends each one long before it.
SESSION_S = 1200

#: Addresses no guest here executes, each with one job: a stopper that lets a headless
#: `resume` run and never fires, the target of a run meant to end at its bound, and the
#: control of a run meant to arrive. Bytes of the interrupt vector table are data, never code.
NEVER_RUNS_STOPPER = "0000:0001"
NEVER_RUNS_TARGET = "0000:0003"
NEVER_RUNS_CONTROL = "0000:0005"

#: Where conventional memory ends: a segment at or above it is video memory or ROM, where a
#: code breakpoint is acknowledged and never fires.
CONVENTIONAL_TOP = 0xA000


def cells(*pairs: tuple[str, str]) -> list[Cell]:
    return [Cell(label, source) for label, source in pairs]


# ------------------------------------------------------------------ what a reply promises


def whole(r: dict[str, Any]) -> bool:
    """The envelope every reply carries: `summary` first, `session` last and either null or a
    block saying whether the emulator is alive, `status` one of the two words, and a refusal
    with a `code` from the published table and a `message`."""
    keys = list(r)
    if not keys or keys[0] != "summary" or keys[-1] != "session":
        return False
    ses = r["session"]
    if ses is not None and not (isinstance(ses, dict) and isinstance(ses.get("alive"), bool)):
        return False
    if r.get("status") == "ok":
        return True
    code = r.get("code")
    return (r.get("status") == "INVALID" and isinstance(code, str) and code in contract.CODES
            and bool(r.get("message")))


def ok(r: dict[str, Any]) -> bool:
    return whole(r) and r.get("status") == "ok"


def refused(r: dict[str, Any], *codes: str) -> bool:
    """A well-formed refusal, with one of `codes` when any are named."""
    return whole(r) and r.get("status") == "INVALID" and (not codes or r.get("code") in codes)


def said(r: dict[str, Any], limit: int = 140) -> str:
    """What a reply said, short, for the result line: the exception, else code and summary, and
    first what is wrong with the envelope when that is what fails the cell."""
    if "exception" in r:
        return str(r["exception"])[:limit]
    shape = "" if whole(r) else f"[envelope: keys {list(r)[:1]}...{list(r)[-1:]}] "
    code = f"[{r['code']}] " if r.get("code") else ""
    return (shape + code + str(r.get("summary", r)))[:limit]


def alive(r: dict[str, Any]) -> bool:
    """The session block says a live emulator."""
    ses = r.get("session")
    return isinstance(ses, dict) and ses.get("alive") is True


def no_session(r: dict[str, Any]) -> bool:
    return "session" in r and r["session"] is None


def judged(label: str, *, reply: dict[str, Any], holds: bool) -> None:
    """A cell whose detail is what the reply said, both by name so neither can be swapped."""
    M.judge(label, holds, said(reply))


def hexint(value: Any) -> int | None:
    """A number a reply carries as an integer or as hex text; None when it is neither."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(str(value), 16)
    except ValueError:
        return None


def clock_moved(r: dict[str, Any]) -> float | None:
    """How far a `run_for` moved the pane's emulated clock, in seconds; None when either end is
    unread, so an unread clock can never pass for one that moved."""
    before, after = r.get("emulated_before_s"), r.get("emulated_after_s")
    if not isinstance(before, int | float) or not isinstance(after, int | float):
        return None
    return float(after) - float(before)


def must(r: dict[str, Any], what: str) -> dict[str, Any]:
    """A preparation step that has to have worked: a stopper left armed, or one never armed,
    would move the failure onto whichever cell comes next."""
    if not ok(r):
        raise RuntimeError(f"{what}: {said(r)}")
    return r


def reg_ref(regs: dict[str, Any], seg: str, off: str) -> str:
    """`SEG:OFF` from two registers of a stop, the offset cut to real mode's sixteen bits."""
    return f"{regs[seg]}:{(hexint(regs[off]) or 0) & 0xFFFF:04X}"


def read_bytes(ref: str, length: int) -> bytes:
    r = must(M.call(server.read_memory, ref=ref, length=length), f"{ref} could not be read")
    raw = bytes.fromhex(str(r["hex"]))
    if len(raw) != length:
        raise RuntimeError(f"{ref}: {len(raw)} bytes came back for {length}")
    return raw


def dump_to_file(ref: str, length: int) -> tuple[dict[str, Any], bytes | None]:
    """`memdump` to a fresh path of this run's scratch: the reply, and the bytes when a file
    landed there."""
    dest = Path(M.fresh(".bin"))
    r = M.call(server.memdump, ref=ref, length=length, dest=str(dest))
    return r, dest.read_bytes() if dest.is_file() else None


def read_word(ref: str) -> int:
    return int.from_bytes(read_bytes(ref, 2), "little")


def vector(number: int) -> tuple[int, int]:
    """The segment and offset the interrupt vector table holds for `number`."""
    raw = read_bytes(f"0000:{number * 4:04X}", 4)
    return int.from_bytes(raw[2:], "little"), int.from_bytes(raw[:2], "little")


# ------------------------------------------------------------------ bringing a session up


def isolate(letter: str) -> None:
    """A declaration store of this section's own: declarations persist per conf and re-arm at
    every `start`, so without this a run would write into the owner's own store and inherit
    whatever another session left on the same conf."""
    os.environ["XDG_STATE_HOME"] = tempfile.mkdtemp(prefix=f"dosbox-x-live-matrix-{letter}-")


def session_files() -> tuple[Path | None, Path | None]:
    ses = dstate.STATE.session
    if ses is None:
        return None, None
    return ses.launch.conf, ses.launch.logfile


#: Every emulator a session of this run spawned, whatever became of the session afterwards: the
#: last word on them is this process's.
SPAWNED: list[subprocess.Popen[bytes]] = []


def note_spawn() -> None:
    ses = dstate.STATE.session
    if ses is not None and ses.proc not in SPAWNED:
        SPAWNED.append(ses.proc)


def kill_spawned() -> list[int]:
    """SIGKILL the process group of every spawned emulator still running; answer their pids."""
    left = [p for p in SPAWNED if p.poll() is None]
    for proc in left:
        with contextlib.suppress(OSError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
    return [p.pid for p in left]


def close_whatever() -> None:
    """No machine at a section's edge. It never raises: a teardown that dies takes every later
    section with it. `close` first; then any emulator of this run still alive is killed through
    its own process group and named, because one left on the owner's machine is a defect."""
    note_spawn()
    try:
        if dstate.STATE.session is not None:
            M.call(server.close)
    except Exception as exc:  # noqa: BLE001 -- a teardown reports, it never aborts the run
        print(f"  (teardown) close raised {type(exc).__name__}: {exc}", flush=True)
    finally:
        dstate.STATE.session = None
        dstate.STATE.store = None
        stray = kill_spawned()
        if stray:
            print(f"  (teardown) emulator pid(s) {stray} outlived close and were killed",
                  flush=True)


M.session_files = session_files
M.on_hang = lambda: print(f"  (hang) killed emulator pid(s) {kill_spawned()}", flush=True)
atexit.register(close_whatever)


def boot(conf: Path = PROBE_CONF, cwd: Path = GUEST, **kw: Any) -> dict[str, Any]:
    """`start` with a log and a save directory of this run's own, so nothing lands in the
    guest's or a project's tree. Raises when the machine did not come up: every cell after it
    would be a statement about nothing."""
    kw.setdefault("logfile", M.fresh(".log"))
    kw.setdefault("state_dir", M.fresh("-save"))
    r = M.call(server.start, conf=str(conf), cwd=str(cwd), seconds=SESSION_S, **kw)
    note_spawn()
    return must(r, "start did not come up")


def start_call(**kw: Any) -> dict[str, Any]:
    """`start` as a cell calls it, its spawn recorded like `boot`'s."""
    r = M.call(server.start, **kw)
    note_spawn()
    return r


def resume_until(found: Callable[[dict[str, Any]], bool], what: str, limit: int,
                 seconds: float = 30) -> dict[str, Any]:
    """Resume, stop after stop, until `found` holds for a stop's registers; answer them. A
    resume that does not come back stopped ends the walk, named."""
    for _ in range(limit):
        r = M.call(server.resume, seconds=seconds)
        regs = r.get("registers") if ok(r) and r.get("halted") else None
        if not isinstance(regs, dict):
            raise RuntimeError(f"{what}: the machine did not stop: {said(r)}")
        if found(regs):
            return regs
    raise RuntimeError(f"{what}: not within {limit} stops")


def into_dos() -> None:
    """From the park at the reset vector to a stop inside DOS, at one of its own INT 21h calls,
    with nothing left armed. The vector table is filled from here on."""
    must(M.call(server.breakpoint_interrupt, number=0x21), "arming INT 21h")
    resume_until(lambda _regs: True, "DOS calling INT 21h", 1)
    must(M.call(server.breakpoint_clear, ref="BPINT 21"), "clearing INT 21h")


def exec_of(name: str, limit: int = 12) -> None:
    """Resume until DOS EXECs `name` (INT 21h AH=4Bh, DS:DX naming the file), then clear that
    stopper: the program is being loaded from here on."""
    must(M.call(server.breakpoint_interrupt, number=0x21, ah=0x4B), "arming the EXEC stop")
    resume_until(lambda regs: name.encode() in read_bytes(reg_ref(regs, "DS", "EDX"), 32).upper(),
                 f"DOS EXECing {name}", limit)
    must(M.call(server.breakpoint_clear, ref="BPINT 21 AH=4B"), "clearing the EXEC stop")


def release_running(stopper: str = NEVER_RUNS_STOPPER) -> None:
    """Let the guest run headless with something declared that can stop it and never will."""
    must(M.call(server.breakpoint_at, ref=stopper), "arming the stopper")
    r = M.call(server.resume)
    if not (ok(r) and r.get("halted") is False):
        raise RuntimeError(f"the machine did not run: {said(r)}")


def free_port() -> int:
    """A TCP port nothing listens on right now, for a serial-route session."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return cast(int, s.getsockname()[1])


def _rewrite(conf: Path, program_line: str, into: str, drop_exit: bool) -> Path:
    """A copy of `conf` in this run's scratch with its launch line replaced by `into` and,
    when asked, its `exit` removed. Each substitution has to match exactly once: one that
    matched nothing would leave a case measuring the original under the patched one's name."""
    text = conf.read_text(encoding="utf-8")
    # A function, not a template: `re` reads a backslash in a replacement STRING as an escape,
    # and a DOS path carries one.
    text, n = re.subn(rf"(?m)^{re.escape(program_line)}\s*$", lambda _m: into, text)
    if n != 1:
        raise RuntimeError(f"{conf} does not carry exactly one {program_line!r} line")
    if drop_exit:
        text, n = re.subn(r"(?m)^exit\s*$", "", text)
        if n != 1:
            raise RuntimeError(f"{conf} does not carry exactly one `exit` line")
    out = Path(M.fresh(".conf"))
    out.write_text(text, encoding="utf-8")
    return out


def conf_with_stub(conf: Path, program_line: str) -> Path:
    """`conf` running the server's serial stub before the guest: the one line the serial route
    asks of a conf (REFERENCE.md, Input and the screen)."""
    stub = f'mount g "{PKG / "guest"}"\nG:\\INJECT.COM\nc:\n{program_line}'
    return _rewrite(conf, program_line, stub, drop_exit=False)


def conf_without_launch(conf: Path, program_line: str) -> Path:
    """`conf` with its launch line and its `exit` removed, so `start(program=...)` is what runs
    the guest."""
    return _rewrite(conf, program_line, "", drop_exit=True)
