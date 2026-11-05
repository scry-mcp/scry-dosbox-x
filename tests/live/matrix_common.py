"""Shared by every section of `dosbox_x_live_matrix.py`."""
from __future__ import annotations

import atexit
import contextlib
import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

PKG = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PKG))

from live_private import guest_dir  # noqa: E402
from matrix_ledger import SCRATCH_PREFIX, SUMMARY_VAR, Cell, Ledger  # noqa: E402
from scry_core import app_launch, guardian  # noqa: E402
from scry_core import reply_contract as contract  # noqa: E402

from scry_dosbox_x import (  # noqa: E402
    launch,
    server,
)
from scry_dosbox_x import process as dprocess  # noqa: E402
from scry_dosbox_x import session as ds  # noqa: E402
from scry_dosbox_x import state as dstate  # noqa: E402

__all__ = ["ds", "server"]

M = Ledger(SCRATCH_PREFIX, SUMMARY_VAR)
ENV = dict(os.environ)

GUEST = guest_dir()
PROBE_CONF = GUEST / "probe.conf"
MOUSE_CONF = GUEST / "mouse.conf"
MOUSE_PROGRAM = "MOUSE.COM"

SESSION_S = 1200

#: Addresses no guest executes (interrupt vector table bytes): stopper, bound-ended target, control.
NEVER_RUNS_STOPPER = "0000:0001"
RELEASE_TRIES = 5
RELEASE_SETTLE_S = 0.5
NEVER_RUNS_TARGET = "0000:0003"
NEVER_RUNS_CONTROL = "0000:0005"

#: At or above this segment a code breakpoint is acknowledged and never fires (video memory, ROM).
CONVENTIONAL_TOP = 0xA000
#: Windows expands any `~user` to a profile path without asking whether the account exists.
NO_SUCH_HOME_WHY = "Windows expands any `~user`, so no home is unknown there" \
    if sys.platform == "win32" else ""


def cells(*pairs: tuple[str, str]) -> list[Cell]:
    return [Cell(label, source) for label, source in pairs]


def whole(r: dict[str, Any]) -> bool:
    """The reply envelope: `summary` first, `session` last, valid `status`."""
    keys = list(r)
    if not keys or keys[0] != "summary" or keys[-1] != "session":
        return False
    ses = r["session"]
    if not (isinstance(ses, dict) and isinstance(ses.get("alive"), bool)):
        return False
    if r.get("status") == "ok":
        return True
    code = r.get("code")
    return (r.get("status") == "INVALID" and isinstance(code, str) and code in contract.CODES
            and bool(r.get("message")))


#: How a close ends a session this run launched: asked to leave, by SIGTERM or on Windows by QUIT.
CLOSED_BY = "quit"


def ok(r: dict[str, Any]) -> bool:
    return whole(r) and r.get("status") == "ok"


def refused(r: dict[str, Any], *codes: str) -> bool:
    """A well-formed refusal, with one of `codes` when any are named."""
    return whole(r) and r.get("status") == "INVALID" and (not codes or r.get("code") in codes)


def videos() -> list[dict[str, Any]]:
    listed = M.call(server.captures).get("captures") or []
    return [c for c in listed if isinstance(c, dict) and c.get("kind") == "avi"]


def said(r: dict[str, Any], limit: int = 140) -> str:
    if "exception" in r:
        return str(r["exception"])[:limit]
    shape = "" if whole(r) else f"[envelope: keys {list(r)[:1]}...{list(r)[-1:]}] "
    code = f"[{r['code']}] " if r.get("code") else ""
    return (shape + code + str(r.get("summary", r)))[:limit]


def alive(r: dict[str, Any]) -> bool:
    ses = r.get("session")
    return isinstance(ses, dict) and ses.get("alive") is True


def no_session(r: dict[str, Any]) -> bool:
    return r.get("session") == {"alive": False, "running": False, "altered": False}


def judged(label: str, *, reply: dict[str, Any], holds: bool) -> None:
    M.judge(label, holds, said(reply))


def hexint(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(str(value), 16)
    except ValueError:
        return None


def clock_moved(r: dict[str, Any]) -> float | None:
    """Seconds a `run_for` moved the emulated clock; None when unread."""
    before, after = r.get("emulated_before_s"), r.get("emulated_after_s")
    if not isinstance(before, int | float) or not isinstance(after, int | float):
        return None
    return float(after) - float(before)


def must(r: dict[str, Any], what: str) -> dict[str, Any]:
    if not ok(r):
        raise RuntimeError(f"{what}: {said(r)}")
    return r


#: A bounded `resume` that the machine stopped.
STOPPED = contract.OTHER_STOP


def advanced(r: dict[str, Any], what: str, verdict: str = contract.ELAPSED) -> dict[str, Any]:
    """An advance that ended as `verdict`: a `TIMEOUT` is `status: ok` too."""
    if not ok(r) or r.get("verdict") != verdict:
        raise RuntimeError(f"{what}: {r.get('verdict')}, not {verdict}: {said(r)}")
    return r


def reg_ref(regs: dict[str, Any], seg: str, off: str) -> str:
    return f"{regs[seg]}:{(hexint(regs[off]) or 0) & 0xFFFF:04X}"


def read_bytes(ref: str, length: int) -> bytes:
    r = must(M.call(server.read_memory, ref=ref, length=length), f"{ref} could not be read")
    raw = bytes.fromhex(str(r["hex"]))
    if len(raw) != length:
        raise RuntimeError(f"{ref}: {len(raw)} bytes came back for {length}")
    return raw


def dump_to_file(ref: str, length: int) -> tuple[dict[str, Any], bytes | None]:
    dest = Path(M.fresh(".bin"))
    r = M.call(server.memdump, ref=ref, length=length, dest=str(dest))
    return r, dest.read_bytes() if dest.is_file() else None


def read_word(ref: str) -> int:
    return int.from_bytes(read_bytes(ref, 2), "little")


def vector(number: int) -> tuple[int, int]:
    raw = read_bytes(f"0000:{number * 4:04X}", 4)
    return int.from_bytes(raw[2:], "little"), int.from_bytes(raw[:2], "little")


def isolate(letter: str) -> None:
    """A declaration store of its own: declarations persist per conf and re-arm at every `start`."""
    os.environ["XDG_STATE_HOME"] = str(M.tmp(f"dosbox-x-live-matrix-{letter}-"))


def session_files() -> tuple[Path | None, Path | None]:
    ses = dstate.STATE.session
    if ses is None:
        return None, None
    return ses.launch.conf, ses.launch.logfile


SPAWNED: list[app_launch.Spawned] = []


def note_spawn() -> None:
    ses = dstate.STATE.session
    if ses is not None and ses.proc not in SPAWNED:
        SPAWNED.append(ses.proc)


def kill_spawned() -> list[int]:
    left = [p for p in SPAWNED if p.poll() is None]
    for proc in left:
        dprocess.signal_group(proc.pid, guardian.KILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
    return [p.pid for p in left]


def close_whatever() -> None:
    """No machine at a section's edge; never raises. Kills any emulator `close` left alive."""
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
            print(f"  (teardown) the emulators {stray} outlived close and were killed", flush=True)


M.session_files = session_files
M.on_hang = lambda: print(f"  (hang) killed the emulators {kill_spawned()}", flush=True)
M.on_end = close_whatever
atexit.register(close_whatever)


def boot(conf: Path = PROBE_CONF, cwd: Path = GUEST, **kw: Any) -> dict[str, Any]:
    """`start` with a log and save dir of this run's own; raises when not up."""
    kw.setdefault("logfile", M.fresh(".log"))
    kw.setdefault("state_dir", M.fresh("-save"))
    # The presence edge is for a person watching; only section R asks for it.
    kw.setdefault("presence", False)
    r = M.call(server.start, conf=str(conf), cwd=str(cwd), session_seconds=SESSION_S, **kw)
    note_spawn()
    return must(r, "start did not come up")


def start_call(**kw: Any) -> dict[str, Any]:
    kw.setdefault("presence", False)
    r = M.call(server.start, **kw)
    note_spawn()
    return r


def resume_until(found: Callable[[dict[str, Any]], bool], what: str, limit: int,
                 seconds: float = 30) -> dict[str, Any]:
    for _ in range(limit):
        r = M.call(server.resume, seconds=seconds)
        regs = r.get("regs") if ok(r) and "stop_seq" in r else None
        if not isinstance(regs, dict):
            raise RuntimeError(f"{what}: the machine did not stop: {said(r)}")
        if found(regs):
            return regs
    raise RuntimeError(f"{what}: not within {limit} stops")


def into_dos() -> None:
    must(M.call(server.breakpoint_interrupt, number=0x21), "arming INT 21h")
    resume_until(lambda _regs: True, "DOS calling INT 21h", 1)
    must(M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 21"), "clearing INT 21h")


def exec_of(name: str, limit: int = 12) -> None:
    must(M.call(server.breakpoint_interrupt, number=0x21, ah=0x4B), "arming the EXEC stop")
    resume_until(lambda regs: name.encode() in read_bytes(reg_ref(regs, "DS", "EDX"), 32).upper(),
                 f"DOS EXECing {name}", limit)
    must(M.call(server.declaration_clear, kind="breakpoint", ref="BPINT 21 AH=4B"),
         "clearing the EXEC stop")


def release_running(stopper: str = NEVER_RUNS_STOPPER) -> None:
    must(M.call(server.breakpoint_at, ref=stopper), "arming the stopper")
    r = M.call(server.resume)
    # A wait whose bound ran out with its `VRT` still out leaves that retrace stop armed, and
    # the first release meets it.
    if ok(r) and str(r.get("cause")).startswith("most likely the retrace stop"):
        r = M.call(server.resume)
    if not (ok(r) and "stop_seq" not in r):
        raise RuntimeError(f"the machine did not run: {said(r)}")
    # A pending retrace stop can meet the guest after that reply: settle, then check `status`.
    for _ in range(RELEASE_TRIES):
        time.sleep(RELEASE_SETTLE_S)
        seen = M.call(server.status)
        running = (seen.get("session") or {}).get("running") is True
        if ok(seen) and "stopped_on_its_own" not in seen and running:
            return
        again = M.call(server.resume)
        if not (ok(again) and "stop_seq" not in again):
            raise RuntimeError(f"the machine did not run again: {said(again)}")
    raise RuntimeError("the machine kept stopping on its own after every release")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return cast(int, s.getsockname()[1])


def _rewrite(conf: Path, program_line: str, into: str, drop_exit: bool) -> Path:
    """A scratch copy of `conf` with its launch line replaced and optionally `exit` removed.
    Each substitution must match exactly once, or a case measures the original."""
    text = conf.read_text(encoding="utf-8")
    # A function: `re` treats a backslash in a replacement string as an escape.
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
    """`conf` running the serial stub before the guest (REFERENCE.md, Input and the screen)."""
    stub = f'mount g "{launch.GUEST_DIR}"\nG:\\SCRY.COM\nc:\n{program_line}'
    return _rewrite(conf, program_line, stub, drop_exit=False)


def conf_without_launch(conf: Path, program_line: str) -> Path:
    return _rewrite(conf, program_line, "", drop_exit=True)
