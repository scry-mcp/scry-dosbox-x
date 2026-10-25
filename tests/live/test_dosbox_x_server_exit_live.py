"""However the server ends (stdin closed, SIGTERM, SIGHUP), its DOSBox-X ends with it."""
from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import live_private  # isort: skip -- first: a pooled job's working copies
import pytest
from scry_core import guardian

import dosbox_process as dprocess

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[2]
BRICKS = live_private.bricks_dir()
#: Past the close's own grace (`Session.close`), with room for the server to get there.
GONE_WITHIN_S = 20.0
#: A silent server fails the case instead of hanging it.
ANSWER_WITHIN_S = 90.0


def _rpc(proc: subprocess.Popen[bytes], mid: int, method: str, params: dict[str, Any]) -> Any:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                  "params": params}) + "\n").encode())
    proc.stdin.flush()
    while line := proc.stdout.readline():
        message = json.loads(line)
        if message.get("id") == mid:
            return message
    raise AssertionError(f"the server closed its stdout before answering {method}")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals and process sessions")
@pytest.mark.parametrize("ended_by, code", [("stdin", 0), ("SIGTERM", 128 + signal.SIGTERM),
                                             ("SIGHUP", 128 + getattr(signal, "SIGHUP", 0))])
def test_the_emulator_ends_with_the_server(ended_by: str, code: int, tmp_path: Path) -> None:
    errors = tmp_path / "server.stderr"
    with errors.open("wb") as err:
        proc = subprocess.Popen([sys.executable, str(ROOT / "dosbox_x_server.py")], cwd=ROOT,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
    silent = threading.Timer(ANSWER_WITHIN_S, proc.kill)
    silent.start()
    pid = None
    try:
        _rpc(proc, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "exit-live", "version": "0"}})
        assert proc.stdin is not None
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()
        started = _rpc(proc, 2, "tools/call", {"name": "start", "arguments": {
            "conf": str(BRICKS / "bricks.conf"), "cwd": str(BRICKS), "session_seconds": 120}})
        body = started["result"]["structuredContent"]
        assert body["status"] == "ok", body.get("summary")
        pid = body["pid"]
        assert _alive(pid), "the emulator the start reported is not running"
        if ended_by == "stdin":
            proc.stdin.close()
        else:
            proc.send_signal(getattr(signal, ended_by))
        deadline = time.monotonic() + GONE_WITHIN_S
        while _alive(pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        # `Z` in ps is an emulator gone and not yet reaped; a live server is an unfinished close.
        seen = subprocess.run(["ps", "-o", "pid=,stat=,etime=", "-p", f"{pid},{proc.pid}"],
                              capture_output=True, text=True, check=False).stdout.strip()
        assert not _alive(pid), (f"DOSBox-X {pid} outlived a server ended by {ended_by} by "
                                 f"{GONE_WITHIN_S:g} s; ps: {seen or 'nothing'}; server: "
                                 f"{errors.read_text(errors='replace')[-600:]}")
        assert proc.wait(GONE_WITHIN_S) == code, errors.read_text(errors="replace")[-600:]
    finally:
        silent.cancel()
        if pid is not None and _alive(pid):
            with contextlib.suppress(ProcessLookupError):
                dprocess.signal_group(pid, guardian.KILL)
        if proc.poll() is None:
            proc.kill()
