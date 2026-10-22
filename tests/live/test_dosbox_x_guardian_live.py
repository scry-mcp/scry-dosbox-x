"""The guardian beside DOSBox-X, against the real server over stdio and the real emulator: a
SIGKILLed server, which runs no `finally`, still takes its emulator with it, and a session held at
the debugger ends by the host's clock, just past its `session_seconds`. Each case has its control:
the same ending with the guardian withheld, where the emulator outlives it."""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_dosbox_x_server_exit_live import ANSWER_WITHIN_S, BRICKS, ROOT, _alive, _rpc

import dosbox_process as dprocess

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(sys.platform == "win32", reason="the guardian is POSIX only")]

#: Within a guardian's polls of the ending it watches for.
GONE_WITHIN_S = 10.0
#: The bound the held session is given: short, so the case is too.
BOUND_S = 15
#: The server's own entry, the guardian withheld when told to (the control).
SERVER = """
import sys
sys.path.insert(0, sys.argv[1])
if sys.argv[2] == "bare":
    from scry_core import guardian
    guardian.spawn = lambda *a, **k: None
import dosbox_x_server
dosbox_x_server.main()
"""


def _server(mode: str, err: Any) -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, "-c", SERVER, str(ROOT), mode], cwd=ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)


def _start(proc: subprocess.Popen[bytes], seconds: int) -> int:
    _rpc(proc, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "guardian-live", "version": "0"}})
    assert proc.stdin is not None
    proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    proc.stdin.flush()
    started = _rpc(proc, 2, "tools/call", {"name": "start", "arguments": {
        "conf": str(BRICKS / "bricks.conf"), "cwd": str(BRICKS), "session_seconds": seconds}})
    body = started["result"]["structuredContent"]
    assert body["status"] == "ok", body.get("summary")
    pid = int(body["pid"])
    assert _alive(pid), "the emulator the start reported is not running"
    return pid


def _running(pid: int) -> bool:
    """Whether `pid` still runs: a process killed and not yet reaped by its parent, the live
    server, is a zombie, which has ended."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True,
                          check=False).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def _gone_within(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while _running(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    return not _running(pid)


def _end(proc: subprocess.Popen[bytes], pid: int | None) -> None:
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    proc.wait()
    if pid is not None and _alive(pid):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(pid), signal.SIGKILL)


@pytest.mark.parametrize("mode", ["guarded", "bare"])
def test_a_sigkilled_server_takes_its_emulator_with_it_only_with_the_guardian(
        mode: str, tmp_path: Path) -> None:
    with (tmp_path / "server.stderr").open("wb") as err:
        proc = _server(mode, err)
    silent = threading.Timer(ANSWER_WITHIN_S, proc.kill)
    silent.start()
    pid = None
    try:
        pid = _start(proc, 300)
        proc.send_signal(signal.SIGKILL)
        proc.wait()
        gone = _gone_within(pid, GONE_WITHIN_S)
        assert gone is (mode == "guarded"), (
            f"DOSBox-X {pid} {'outlived' if not gone else 'died with'} a SIGKILLed server, "
            f"{mode}")
    finally:
        silent.cancel()
        _end(proc, pid)


@pytest.mark.parametrize("mode", ["guarded", "bare"])
def test_a_session_held_at_the_debugger_ends_at_its_bound_only_with_the_guardian(
        mode: str, tmp_path: Path) -> None:
    with (tmp_path / "server.stderr").open("wb") as err:
        proc = _server(mode, err)
    silent = threading.Timer(ANSWER_WITHIN_S + BOUND_S + dprocess.GUARDIAN_GRACE_S, proc.kill)
    silent.start()
    pid = None
    try:
        pid = _start(proc, BOUND_S)              # parked at the debugger, and left there
        gone = _gone_within(pid, BOUND_S + dprocess.GUARDIAN_GRACE_S + GONE_WITHIN_S)
        assert gone is (mode == "guarded"), (
            f"DOSBox-X {pid} {'outlived' if not gone else 'ended at'} its {BOUND_S} s bound, "
            f"{mode}")
        assert proc.poll() is None, "the bound took the server too"
    finally:
        silent.cancel()
        _end(proc, pid)
